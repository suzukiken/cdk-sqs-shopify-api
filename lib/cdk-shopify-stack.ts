import * as cdk from '@aws-cdk/core';
import * as sqs from "@aws-cdk/aws-sqs";
import * as lambda from "@aws-cdk/aws-lambda";
import { SqsEventSource } from "@aws-cdk/aws-lambda-event-sources";
import { PythonFunction } from "@aws-cdk/aws-lambda-python";
import * as secretsmanager from '@aws-cdk/aws-secretsmanager';
import * as dynamodb from '@aws-cdk/aws-dynamodb';
import * as iam from '@aws-cdk/aws-iam';

export class CdkShopifyStack extends cdk.Stack {
  constructor(scope: cdk.Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);
    
    const secret_dev = secretsmanager.Secret.fromSecretNameV2(this, 'SecretDev', 'shopify/figmentresearchshop1/app/private')
    const secret_prod = secretsmanager.Secret.fromSecretNameV2(this, 'SecretProd', 'shopify/figmentres/app/apicalltest')
    
    // Dynamodb
    
    const table = new dynamodb.Table(this, "Table", {
      partitionKey: {
        name: "id",
        type: dynamodb.AttributeType.STRING,
      },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      pointInTimeRecovery: true
    })
    
    table.addGlobalSecondaryIndex({
      indexName: "batch-epoch-index",
      partitionKey: {
        name: "batch",
        type: dynamodb.AttributeType.STRING,
      },
      sortKey: {
        name: "epoch",
        type: dynamodb.AttributeType.NUMBER,
      },
    })
    
    table.addGlobalSecondaryIndex({
      indexName: "error-epoch-index",
      partitionKey: {
        name: "error",
        type: dynamodb.AttributeType.STRING,
      },
      sortKey: {
        name: "epoch",
        type: dynamodb.AttributeType.NUMBER,
      },
    })
    
    // DLQ
    
    const notification_function = new PythonFunction(this, "Notification", {
      entry: "lambda",
      index: "error_notification.py",
      handler: "lambda_handler",
      runtime: lambda.Runtime.PYTHON_3_8,
      environment: {
        TABLE_NAME: table.tableName
      },
    })
    
    // DLQ and its lambda which will be triggered by dlq
    
    const dead_letter_queue = new sqs.Queue(this, "DLQ", {
      retentionPeriod: cdk.Duration.minutes(60),
    })
    
    notification_function.addEventSource(
      new SqsEventSource(dead_letter_queue)
    )

    table.grantReadWriteData(notification_function)
    dead_letter_queue.grantConsumeMessages(notification_function)
    
    // queue

    const queue = new sqs.Queue(this, "Queue", {
      retentionPeriod: cdk.Duration.minutes(10),
      visibilityTimeout: cdk.Duration.seconds(15),
      deadLetterQueue: {
        maxReceiveCount: 10, 
        queue: dead_letter_queue,
      },
    })
    
    // Lambda
    
    const role = new iam.Role(this, "Role", {
      assumedBy: new iam.ServicePrincipal("lambda.amazonaws.com"),
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName("service-role/AWSLambdaBasicExecutionRole"),
        iam.ManagedPolicy.fromAwsManagedPolicyName("CloudWatchLambdaInsightsExecutionRolePolicy")
      ]
    })
    
    const layer = lambda.LayerVersion.fromLayerVersionArn(this, "layer", 
      "arn:aws:lambda:ap-northeast-1:580247275435:layer:LambdaInsightsExtension:14"
    )

    const lambda_function = new PythonFunction(this, "Function", {
      entry: "lambda",
      index: "shopify_inventory.py",
      handler: "lambda_handler",
      runtime: lambda.Runtime.PYTHON_3_8,
      timeout: cdk.Duration.seconds(10),
      role: role,
      layers: [ layer ],
      environment: {
        SHOPIFY_PASSWORD_DEV: secret_dev.secretValueFromJson('PASSWORD').toString(),
        SHOPIFY_SHOP_DEV: secret_dev.secretValueFromJson('SHOP').toString(),
        SHOPIFY_PASSWORD_PROD: secret_prod.secretValueFromJson('PASSWORD').toString(),
        SHOPIFY_SHOP_PROD: secret_prod.secretValueFromJson('SHOP').toString(),
        TABLE_NAME: table.tableName
      },
      //reservedConcurrentExecutions: 10,
    })
    
    lambda_function.addEventSource(
      new SqsEventSource(queue, { batchSize: 1 })
    )
    
    table.grantReadWriteData(lambda_function)
    queue.grantConsumeMessages(lambda_function)
    
    new cdk.CfnOutput(this, "OutputQueue", {
      value: queue.queueName
    })
    
    new cdk.CfnOutput(this, 'OutputTable', { 
      value: table.tableName,
    })
  }
}
